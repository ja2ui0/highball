"""
Container command builder for backup/restore operations
Handles Docker/Podman container execution with proper mounting and environment setup
"""
from typing import Dict, List, Optional
from enum import Enum
import shlex


class MountStrategy(Enum):
    """Different mounting strategies for container operations"""
    BACKUP_SOURCES = "backup_sources"
    RESTORE_TO_HIGHBALL = "restore_to_highball" 
    RESTORE_TO_SOURCE = "restore_to_source"


class ContainerCommandBuilder:
    """Builds container commands with proper mounting and environment setup"""
    
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
        mount_paths: List[str] = None,
        target_path: str = None
    ) -> List[str]:
        """Build complete container command with proper mounting and environment"""
        cmd = []
        
        # Add resource management for CPU-intensive operations (wrap the entire container)
        if command_type in ['backup', 'restore', 'prune', 'check']:
            cmd.extend(['nice', '-n', '5', 'ionice', '-c', '2', '-n', '4'])
        
        # Add container runtime command
        cmd.extend([self.container_runtime, 'run', '--rm', '--user', '$(id -u):$(id -g)'])
        
        # Add environment variables
        cmd.extend(self._build_environment_flags(environment_vars))
        
        # Add mount points based on strategy
        cmd.extend(self._build_mount_flags(mount_strategy, mount_paths, target_path))
        
        # Add container image
        cmd.append(self.restic_image)
        
        # Add restic command (restic/restic:0.18.0 already has restic as entrypoint)
        cmd.extend(['-r', repository_url, command_type])
        
        # Add arguments
        if args:
            cmd.extend(args)
            
        # Add source paths for backup operations
        if command_type == 'backup' and mount_paths:
            cmd.extend(mount_paths)
        
        return cmd
    
    def build_ssh_command(
        self,
        hostname: str,
        username: str,
        container_command: List[str]
    ) -> List[str]:
        """Build SSH command to execute container on remote host"""
        # Convert container command to shell string with proper quote handling
        container_cmd_str = shlex.join(container_command)
        # Allow shell evaluation of $(id -u):$(id -g) on remote host
        container_cmd_str = container_cmd_str.replace("'$(id -u):$(id -g)'", "$(id -u):$(id -g)")
        
        ssh_cmd = [
            'ssh', '-o', 'ConnectTimeout=30', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'LogLevel=ERROR',
            f"{username}@{hostname}",
            container_cmd_str
        ]
        
        return ssh_cmd
    
    def _build_environment_flags(self, environment_vars: Dict[str, str]) -> List[str]:
        """Build environment variable flags for container"""
        flags = []
        for key, value in environment_vars.items():
            flags.extend(['-e', f'{key}={value}'])
        return flags
    
    def _build_mount_flags(
        self,
        strategy: MountStrategy,
        mount_paths: List[str] = None,
        target_path: str = None
    ) -> List[str]:
        """Build mount flags based on mounting strategy"""
        flags = []
        
        if strategy == MountStrategy.BACKUP_SOURCES and mount_paths:
            # Mount source paths as read-only for backup
            for path in mount_paths:
                flags.extend(['-v', f'{path}:{path}:ro'])
                
        elif strategy == MountStrategy.RESTORE_TO_HIGHBALL and target_path:
            # Mount target directory for restore to Highball
            flags.extend(['-v', f'{target_path}:/restore-target'])
            
        elif strategy == MountStrategy.RESTORE_TO_SOURCE and mount_paths:
            # Mount snapshot paths for restore to source
            for path in mount_paths:
                flags.extend(['-v', f'{path}:{path}'])
        
        return flags