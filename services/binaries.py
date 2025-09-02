"""
DEPRECATED: Legacy Container Service - Use services.global.ResticContainerFactory instead
This file exists for backward compatibility during refactor
"""
from typing import Dict, List, Optional
from services.shared import ResticContainerFactory, SSHCommandFactory, MountStrategy


class ContainerCommandBuilder:
    """DEPRECATED: Use services.global.ResticContainerFactory instead"""
    
    def __init__(self, container_runtime: str = 'docker'):
        self.factory = ResticContainerFactory(container_runtime)
    
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
        """DEPRECATED: Delegate to services.global.ResticContainerFactory"""
        return self.factory.build_container_command(
            command_type, repository_url, args, environment_vars, 
            mount_strategy, source_paths, restore_target
        )
    
    # _get_volume_mounts moved to services.global.ResticContainerFactory
    
    def build_ssh_container_command(
        self,
        ssh_hostname: str,
        ssh_username: str,
        container_command: List[str]
    ) -> List[str]:
        """DEPRECATED: Delegate to services.global factories"""
        ssh_factory = SSHCommandFactory()
        return self.factory.wrap_with_ssh(container_command, ssh_hostname, ssh_username, ssh_factory)
    
    def build_backup_command(
        self,
        repository_url: str,
        source_paths: List[str],
        environment_vars: Dict[str, str],
        backup_args: Optional[List[str]] = None
    ) -> List[str]:
        """DEPRECATED: Delegate to services.global.ResticContainerFactory"""
        return self.factory.build_backup_command(
            repository_url, source_paths, environment_vars, backup_args
        )
    
    def build_restore_command(
        self,
        repository_url: str,
        snapshot_id: str,
        environment_vars: Dict[str, str],
        restore_to_highball: bool = True,
        restore_args: Optional[List[str]] = None
    ) -> List[str]:
        """DEPRECATED: Delegate to services.global.ResticContainerFactory"""
        return self.factory.build_restore_command(
            repository_url, snapshot_id, environment_vars, restore_to_highball, restore_args
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