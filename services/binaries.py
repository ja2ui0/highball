"""
Unified Container Service
Consolidates binary checking and container command building
Replaces: binary_checker_service.py, container_command_builder.py
"""
from typing import Dict, List, Optional, Any
from enum import Enum
import shlex


# =============================================================================
# **DATA STRUCTURES** - Container and binary configuration
# =============================================================================

class MountStrategy(Enum):
    """Different mounting strategies for container operations"""
    BACKUP_SOURCES = "backup_sources"
    RESTORE_TO_HIGHBALL = "restore_to_highball" 
    RESTORE_TO_SOURCE = "restore_to_source"


# **CONTAINER COMMAND BUILDING CONCERN** - Generate container execution commands
# =============================================================================

class ContainerCommandBuilder:
    """Container command building - ONLY handles container command construction"""
    
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
        """Container concern: build complete container execution command"""
        
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
        """Container concern: generate volume mount specifications based on strategy"""
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
    
    def build_ssh_container_command(
        self,
        ssh_hostname: str,
        ssh_username: str,
        container_command: List[str]
    ) -> List[str]:
        """Container concern: wrap container command in SSH execution"""
        # Escape the container command for SSH execution
        escaped_cmd = shlex.join(container_command)
        
        return [
            'ssh',
            '-o', 'ConnectTimeout=10',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'{ssh_username}@{ssh_hostname}',
            escaped_cmd
        ]
    
    def build_backup_command(
        self,
        repository_url: str,
        source_paths: List[str],
        environment_vars: Dict[str, str],
        backup_args: Optional[List[str]] = None
    ) -> List[str]:
        """Container concern: build backup-specific container command"""
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
        """Container concern: build restore-specific container command"""
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


# =============================================================================
# **UNIFIED SERVICE FACADE** - Orchestrates binary checking and container building
# =============================================================================

class ContainerService:
    """Unified container service - ONLY coordinates between container concerns"""
    
    def __init__(self, container_runtime: str = 'docker'):
        self.command_builder = ContainerCommandBuilder(container_runtime)
    
    
    # **CONTAINER BUILDING DELEGATION** - Pure delegation to building concern
    def build_backup_container_command(
        self,
        repository_url: str,
        source_paths: List[str],
        environment_vars: Dict[str, str],
        backup_args: Optional[List[str]] = None
    ) -> List[str]:
        """Delegation: build backup container command"""
        return self.command_builder.build_backup_command(
            repository_url, source_paths, environment_vars, backup_args
        )
    
    def build_restore_container_command(
        self,
        repository_url: str,
        snapshot_id: str,
        environment_vars: Dict[str, str],
        restore_to_highball: bool = True,
        restore_args: Optional[List[str]] = None
    ) -> List[str]:
        """Delegation: build restore container command"""
        return self.command_builder.build_restore_command(
            repository_url, snapshot_id, environment_vars, restore_to_highball, restore_args
        )
    
    def build_ssh_container_command(
        self,
        ssh_hostname: str,
        ssh_username: str,
        container_command: List[str]
    ) -> List[str]:
        """Delegation: wrap container command for SSH execution"""
        return self.command_builder.build_ssh_container_command(ssh_hostname, ssh_username, container_command)