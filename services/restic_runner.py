"""
Restic backup service
Handles Restic backup operations via SSH execution, similar to rsync pattern
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import shlex
from services.container_command_builder import ContainerCommandBuilder, MountStrategy
from services.snapshot_introspection_service import SnapshotIntrospectionService
from services.restic_argument_builder import ResticArgumentBuilder


class TransportType(Enum):
    """Transport methods for Restic operations"""
    LOCAL = "local"
    SSH = "ssh"
    CONTAINER = "container"


class CommandType(Enum):
    """Types of Restic commands"""
    INIT = "init"
    BACKUP = "backup"
    RESTORE = "restore"
    CHECK = "check"
    FORGET = "forget"
    PRUNE = "prune"
    SNAPSHOTS = "snapshots"


@dataclass
class ResticCommand:
    """Planned Restic command for SSH execution"""
    command_type: CommandType
    transport: TransportType
    ssh_config: Optional[Dict[str, str]] = None  # {hostname, username} for SSH
    repository_url: str = ""
    source_paths: List[str] = None
    args: List[str] = None
    environment_vars: Dict[str, str] = None
    timeout_seconds: int = 3600
    job_config: Optional[Dict] = None  # Job config for container runtime access
    
    def to_ssh_command(self) -> List[str]:
        """Convert to SSH command array for container execution on remote host"""
        if self.transport != TransportType.SSH:
            return self.to_local_command()
        
        # Build container command for remote execution
        container_cmd = self._build_container_command(self.job_config)
        
        # Use ContainerCommandBuilder for SSH command construction
        container_builder = ContainerCommandBuilder(self.job_config.get('container_runtime', 'docker'))
        return container_builder.build_ssh_command(
            self.ssh_config['hostname'],
            self.ssh_config['username'],
            container_cmd
        )
    
    def to_local_command(self) -> List[str]:
        """Convert to local restic command for container execution"""
        cmd = ["restic", "-r", self.repository_url]
        
        # Add command type (backup, restore, etc.)
        cmd.append(self.command_type.value)
        
        if self.args:
            cmd.extend(self.args)
        if self.source_paths and self.command_type == CommandType.BACKUP:
            cmd.extend(self.source_paths)
        return cmd
    
    def _build_container_command(self, job_config: Dict = None) -> List[str]:
        """Build container run command with restic official container"""
        runtime = job_config.get('container_runtime', 'docker') if job_config else 'docker'
        container_builder = ContainerCommandBuilder(runtime)
        
        # Determine mount strategy and paths
        mount_strategy, mount_paths, target_path = self._determine_mount_strategy()
        
        # Adjust arguments for container execution
        adjusted_args = ResticArgumentBuilder.adjust_args_for_container(self.args or [])
        
        return container_builder.build_container_command(
            command_type=self.command_type.value,
            repository_url=self.repository_url,
            args=adjusted_args,
            environment_vars=self.environment_vars or {},
            mount_strategy=mount_strategy,
            mount_paths=mount_paths,
            target_path=target_path
        )
    
    def _determine_mount_strategy(self) -> tuple:
        """Determine mount strategy, paths, and target based on command type"""
        if self.command_type == CommandType.BACKUP:
            return MountStrategy.BACKUP_SOURCES, self.source_paths, None
            
        elif self.command_type == CommandType.RESTORE:
            target_path = ResticArgumentBuilder.extract_target_from_args(self.args or [])
            
            if target_path == '/' and hasattr(self, 'job_config') and self.job_config:
                # Restore-to-source: introspect snapshot for mount paths
                snapshot_id = ResticArgumentBuilder.extract_snapshot_id_from_args(self.args or [])
                if snapshot_id:
                    snapshot_paths = self._get_snapshot_root_paths(snapshot_id)
                    return MountStrategy.RESTORE_TO_SOURCE, snapshot_paths, None
                    
            elif target_path:
                # Restore-to-highball: mount target directory
                return MountStrategy.RESTORE_TO_HIGHBALL, None, target_path
                
        return MountStrategy.BACKUP_SOURCES, [], None
    
    
    def _get_snapshot_root_paths(self, snapshot_id: str) -> List[str]:
        """Get root paths from snapshot by introspecting its contents"""
        if not snapshot_id or not hasattr(self, 'job_config') or not self.job_config:
            return []
        
        # Use SnapshotIntrospectionService for cleaner separation of concerns
        introspection_service = SnapshotIntrospectionService()
        dest_config = self.job_config.get('dest_config', {})
        repo_url = self._build_repository_url(dest_config)
        env_vars = self._build_environment(dest_config)
        
        ssh_config = None
        if self.transport == TransportType.SSH:
            ssh_config = self.ssh_config
            
        return introspection_service.get_snapshot_source_paths(
            snapshot_id=snapshot_id,
            repository_url=repo_url,
            environment_vars=env_vars,
            ssh_config=ssh_config,
            container_runtime=self.job_config.get('container_runtime', 'docker')
        )
    
    def _build_repository_url(self, dest_config: Dict) -> str:
        """Get Restic repository URL from destination config"""
        return dest_config.get('repo_uri', dest_config.get('dest_string', '/tmp/restic-repo'))
    
    def _build_environment(self, dest_config: Dict) -> Dict[str, str]:
        """Build environment variables for Restic execution"""
        env = {}
        if 'password' in dest_config:
            env['RESTIC_PASSWORD'] = dest_config['password']
        return env
    


@dataclass
class ResticPlan:
    """Complete execution plan for a Restic job"""
    job_name: str
    commands: List[ResticCommand]
    estimated_duration_minutes: int
    requires_binary_check: bool = True
    requires_init: bool = False
    retention_policy: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """Convert plan to dictionary for JSON serialization"""
        return {
            "job_name": self.job_name,
            "commands": [
                {
                    "type": cmd.command_type.value,
                    "transport": cmd.transport.value,
                    "repository": cmd.repository_url,
                    "source_paths": cmd.source_paths,
                    "timeout": cmd.timeout_seconds,
                    "ssh_target": f"{cmd.ssh_config['username']}@{cmd.ssh_config['hostname']}" if cmd.ssh_config else None
                } for cmd in self.commands
            ],
            "estimated_duration": self.estimated_duration_minutes,
            "requires_binary_check": self.requires_binary_check,
            "requires_init": self.requires_init,
            "retention_policy": self.retention_policy,
            "next_steps": [
                "Verify restic binary exists on source system",
                "Initialize repository if needed",
                "Execute backup with streaming progress",
                "Parse JSON output for metrics",
                "Apply retention policy if configured",
                "Handle secrets securely via environment variables"
            ]
        }


class ResticRunner:
    """Service for planning Restic backup operations via SSH"""
    
    def __init__(self):
        self.default_timeout = 3600  # 1 hour
    
    def plan_backup_job(self, job_config: Dict) -> ResticPlan:
        """Create execution plan for backup job"""
        job_name = job_config.get('name', 'unnamed')
        
        # Determine transport and SSH config
        transport, ssh_config = self._determine_transport(job_config)
        
        # Parse repository configuration
        repository_url = self._build_repository_url(job_config.get('dest_config', {}))
        
        # Parse environment variables (secrets)
        environment_vars = self._build_environment(job_config.get('dest_config', {}))
        
        # Parse source paths
        source_paths = self._parse_source_paths(job_config.get('source_config', {}))
        
        # Build command sequence
        commands = []
        
        # Repository initialization (if needed)
        if job_config.get('dest_config', {}).get('auto_init', False):
            init_cmd = ResticCommand(
                command_type=CommandType.INIT,
                transport=transport,
                ssh_config=ssh_config,
                repository_url=repository_url,
                environment_vars=environment_vars,
                args=[],
                job_config=job_config
            )
            commands.append(init_cmd)
        
        # Main backup command
        backup_args = ResticArgumentBuilder.build_backup_args(job_config)
        backup_cmd = ResticCommand(
            command_type=CommandType.BACKUP,
            transport=transport,
            ssh_config=ssh_config,
            repository_url=repository_url,
            source_paths=source_paths,
            args=backup_args,
            environment_vars=environment_vars,
            timeout_seconds=job_config.get('timeout', self.default_timeout),
            job_config=job_config
        )
        commands.append(backup_cmd)
        
        # Retention policy (if configured)
        retention = job_config.get('retention_policy')
        if retention:
            forget_args = ResticArgumentBuilder.build_retention_args(retention)
            forget_cmd = ResticCommand(
                command_type=CommandType.FORGET,
                transport=transport,
                ssh_config=ssh_config,
                repository_url=repository_url,
                args=forget_args,
                environment_vars=environment_vars,
                job_config=job_config
            )
            commands.append(forget_cmd)
            
            # Prune after forget
            prune_cmd = ResticCommand(
                command_type=CommandType.PRUNE,
                transport=transport,
                ssh_config=ssh_config,
                repository_url=repository_url,
                args=[],
                environment_vars=environment_vars,
                job_config=job_config
            )
            commands.append(prune_cmd)
        
        return ResticPlan(
            job_name=job_name,
            commands=commands,
            estimated_duration_minutes=self._estimate_duration(job_config),
            requires_binary_check=transport == TransportType.SSH,
            requires_init=job_config.get('dest_config', {}).get('auto_init', False),
            retention_policy=retention
        )
    
    def plan_restore_job(self, job_config: Dict, restore_config: Dict) -> ResticPlan:
        """Create execution plan for restore job"""
        job_name = job_config.get('name', 'unnamed')
        
        # Determine transport and target host for restore
        transport, ssh_config = self._determine_restore_transport(job_config, restore_config)
        
        # Parse repository configuration (same as backup)
        repository_url = self._build_repository_url(job_config.get('dest_config', {}))
        
        # Parse environment variables (same as backup)
        environment_vars = self._build_environment(job_config.get('dest_config', {}))
        
        # Build restore command - pass job_config in restore_config for path mapping
        restore_config_with_job = {**restore_config, 'job_config': job_config}
        restore_args = ResticArgumentBuilder.build_restore_args(restore_config_with_job)
        restore_cmd = ResticCommand(
            command_type=CommandType.RESTORE,
            transport=transport,
            ssh_config=ssh_config,
            repository_url=repository_url,
            source_paths=None,  # Restore doesn't use source_paths
            args=restore_args,
            environment_vars=environment_vars,
            timeout_seconds=restore_config.get('timeout', self.default_timeout)
        )
        
        # Store job config reference for container runtime access
        restore_cmd.job_config = job_config
        
        return ResticPlan(
            job_name=job_name,
            commands=[restore_cmd],
            estimated_duration_minutes=self._estimate_restore_duration(restore_config),
            requires_binary_check=transport == TransportType.SSH,
            requires_init=False,  # Restore never needs init
            retention_policy=None
        )
    
    def _determine_transport(self, job_config: Dict) -> tuple:
        """Determine transport method and SSH config"""
        source_type = job_config.get('source_type', 'local')
        
        if source_type == 'ssh':
            source_config = job_config.get('source_config', {})
            ssh_config = {
                'hostname': source_config.get('hostname', ''),
                'username': source_config.get('username', '')
            }
            return TransportType.SSH, ssh_config
        elif source_type == 'local':
            return TransportType.LOCAL, None
        else:
            return TransportType.CONTAINER, None
    
    def _build_repository_url(self, dest_config: Dict) -> str:
        """Get Restic repository URL from destination config"""
        # The form parser now builds the complete URI, so we just use it
        return dest_config.get('repo_uri', dest_config.get('dest_string', '/tmp/restic-repo'))
    
    def _build_environment(self, dest_config: Dict) -> Dict[str, str]:
        """Build environment variables for Restic execution"""
        env = {}
        
        # Repository password
        if 'password' in dest_config:
            env['RESTIC_PASSWORD'] = dest_config['password']
        
        # S3 credentials
        if 'aws_access_key' in dest_config:
            env['AWS_ACCESS_KEY_ID'] = dest_config['aws_access_key']
        if 'aws_secret_key' in dest_config:
            env['AWS_SECRET_ACCESS_KEY'] = dest_config['aws_secret_key']
        
        # Additional environment variables
        env.update(dest_config.get('environment_vars', {}))
        
        # Add cache environment variables to prevent permission issues
        env.update({
            'HOME': '/tmp',
            'XDG_CACHE_HOME': '/tmp/.cache'
        })
        
        return env
    
    def _parse_source_paths(self, source_config: Dict) -> List[str]:
        """Parse source paths from source configuration - requires source_paths array format"""
        source_paths = source_config.get('source_paths', [])
        if not source_paths:
            raise ValueError("source_config must contain 'source_paths' array - legacy single path format not supported")
        
        # Extract path strings from the source_paths array
        path_strings = []
        for path_config in source_paths:
            if isinstance(path_config, dict):
                path_strings.append(path_config.get('path', ''))
            else:
                path_strings.append(str(path_config))
        
        # Filter out empty paths
        path_strings = [path for path in path_strings if path.strip()]
        
        if not path_strings:
            raise ValueError("source_paths array contains no valid paths")
        
        return path_strings
    
    
    
    def _estimate_duration(self, job_config: Dict) -> int:
        """Estimate backup duration in minutes"""
        # Simple heuristic based on data size or default
        size_hint = job_config.get('estimated_size_gb', 1)
        return max(10, min(180, size_hint * 3))  # 3 minutes per GB, 10-180 min range
    
    def _determine_restore_transport(self, job_config: Dict, restore_config: Dict) -> tuple:
        """Determine transport method and SSH config for restore operations"""
        restore_target = restore_config.get('restore_target', 'highball')
        
        if restore_target == 'source':
            # Restore to source - use source host credentials
            source_type = job_config.get('source_type', 'local')
            if source_type == 'ssh':
                source_config = job_config.get('source_config', {})
                ssh_config = {
                    'hostname': source_config.get('hostname', ''),
                    'username': source_config.get('username', '')
                }
                return TransportType.SSH, ssh_config
            elif source_type == 'local':
                return TransportType.LOCAL, None
            else:
                return TransportType.CONTAINER, None
        else:
            # Restore to Highball - always local execution
            return TransportType.LOCAL, None
    
    
    def _estimate_restore_duration(self, restore_config: Dict) -> int:
        """Estimate restore duration in minutes"""
        # Simple heuristic - restores are typically faster than backups
        if restore_config.get('select_all', False):
            return 30  # Full restore
        else:
            path_count = len(restore_config.get('selected_paths', []))
            return max(5, min(60, path_count * 2))  # 2 minutes per selected path
    
    def plan_init_repository(self, job_config: Dict) -> List[ResticCommand]:
        """Create execution plan for repository initialization"""
        # Determine transport and SSH config
        transport, ssh_config = self._determine_transport(job_config)
        
        # Parse repository configuration
        repository_url = self._build_repository_url(job_config.get('dest_config', {}))
        
        # Parse environment variables (secrets)
        environment_vars = self._build_environment(job_config.get('dest_config', {}))
        
        # Create init command
        init_cmd = ResticCommand(
            command_type=CommandType.INIT,
            transport=transport,
            ssh_config=ssh_config,
            repository_url=repository_url,
            environment_vars=environment_vars,
            args=[],
            job_config=job_config
        )
        
        return [init_cmd]