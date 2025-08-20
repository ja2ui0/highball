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


# =============================================================================
# **BINARY AVAILABILITY CONCERN** - Check for backup tool availability
# =============================================================================

class BinaryCheckerService:
    """Binary availability checking - ONLY handles binary detection and versioning"""
    
    SUPPORTED_BINARIES = {
        'restic': {
            'version_command': 'restic version',
            'description': 'Restic backup tool'
        },
        'borg': {
            'version_command': 'borg --version',
            'description': 'Borg backup tool'
        },
        'kopia': {
            'version_command': 'kopia --version',
            'description': 'Kopia backup tool'
        },
        'rclone': {
            'version_command': 'rclone version --check=false',
            'description': 'Rclone cloud storage tool'
        }
    }
    
    def __init__(self):
        from services.execution import ExecutionService
        self.executor = ExecutionService()
    
    def check_binary_availability(self, binary_name: str, ssh_config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Binary concern: check if backup binary is available locally or remotely"""
        if binary_name not in self.SUPPORTED_BINARIES:
            return {
                'available': False,
                'error': f'Unsupported binary: {binary_name}',
                'supported_binaries': list(self.SUPPORTED_BINARIES.keys())
            }
        
        binary_info = self.SUPPORTED_BINARIES[binary_name]
        version_command = binary_info['version_command'].split()
        
        try:
            if ssh_config:
                # Check on remote host via SSH
                result = self.executor.execute_ssh_command(
                    ssh_config['hostname'],
                    ssh_config['username'],
                    version_command
                )
            else:
                # Check locally
                result = self.executor.execute_local_command(version_command)
            
            if result.returncode == 0:
                return {
                    'available': True,
                    'version': result.stdout.strip(),
                    'description': binary_info['description'],
                    'location': 'remote' if ssh_config else 'local'
                }
            else:
                return {
                    'available': False,
                    'error': f'{binary_name} not found or not executable',
                    'stderr': result.stderr.strip() if result.stderr else None
                }
                
        except Exception as e:
            return {
                'available': False,
                'error': f'Failed to check {binary_name}: {str(e)}'
            }
    
    def check_container_runtime_availability(self, ssh_config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Binary concern: check for container runtime availability (docker/podman)"""
        runtimes = ['podman', 'docker']  # Prefer podman over docker
        
        for runtime in runtimes:
            try:
                version_command = [runtime, '--version']
                
                if ssh_config:
                    result = self.executor.execute_ssh_command(
                        ssh_config['hostname'],
                        ssh_config['username'],
                        version_command
                    )
                else:
                    result = self.executor.execute_local_command(version_command)
                
                if result.returncode == 0:
                    return {
                        'available': True,
                        'runtime': runtime,
                        'version': result.stdout.strip(),
                        'location': 'remote' if ssh_config else 'local'
                    }
                    
            except Exception:
                continue
        
        return {
            'available': False,
            'error': 'No container runtime found (tried: podman, docker)'
        }
    
    def get_system_capabilities(self, ssh_config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Binary concern: get comprehensive system capabilities for backup operations"""
        capabilities = {
            'binaries': {},
            'container_runtime': None,
            'location': 'remote' if ssh_config else 'local'
        }
        
        # Check all supported binaries
        for binary_name in self.SUPPORTED_BINARIES:
            capabilities['binaries'][binary_name] = self.check_binary_availability(binary_name, ssh_config)
        
        # Check container runtime
        runtime_check = self.check_container_runtime_availability(ssh_config)
        if runtime_check['available']:
            capabilities['container_runtime'] = runtime_check['runtime']
        
        return capabilities


# =============================================================================
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
        self.binary_checker = BinaryCheckerService()
        self.command_builder = ContainerCommandBuilder(container_runtime)
    
    # **BINARY CHECKING DELEGATION** - Pure delegation to binary concern
    def check_binary(self, binary_name: str, ssh_config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Delegation: check binary availability"""
        return self.binary_checker.check_binary_availability(binary_name, ssh_config)
    
    def check_container_runtime(self, ssh_config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Delegation: check container runtime availability"""
        return self.binary_checker.check_container_runtime_availability(ssh_config)
    
    def get_system_capabilities(self, ssh_config: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Delegation: get system capabilities"""
        return self.binary_checker.get_system_capabilities(ssh_config)
    
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