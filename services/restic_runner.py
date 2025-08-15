"""
Restic backup service
Handles Restic backup operations via SSH execution, similar to rsync pattern
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
import shlex


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
        
        # Build the full command with user ID expansion on remote host
        # We need the remote host to evaluate $(id -u):$(id -g), not the local host
        container_cmd_str = shlex.join(container_cmd)
        # Replace the literal string with one that will be evaluated on remote host
        container_cmd_str = container_cmd_str.replace("'$(id -u):$(id -g)'", "$(id -u):$(id -g)")
        
        # Build SSH command to execute container on remote host
        ssh_cmd = [
            'ssh', '-o', 'ConnectTimeout=30', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'LogLevel=ERROR',  # Suppress known_hosts warnings
            f"{self.ssh_config['username']}@{self.ssh_config['hostname']}",
            container_cmd_str  # Use modified string that allows shell evaluation
        ]
        
        return ssh_cmd
    
    def to_local_command(self) -> List[str]:
        """Convert to local restic command for container execution"""
        cmd = ["restic", "-r", self.repository_url]
        if self.args:
            cmd.extend(self.args)
        if self.source_paths and self.command_type == CommandType.BACKUP:
            cmd.extend(self.source_paths)
        return cmd
    
    def _build_container_command(self, job_config: Dict = None) -> List[str]:
        """Build container run command with restic official container"""
        # Get container runtime from job config
        runtime = job_config.get('container_runtime', 'docker') if job_config else 'docker'
        
        cmd = [runtime, 'run', '--rm', '--user', '$(id -u):$(id -g)']
        
        # Add environment variables
        if self.environment_vars:
            for key, value in self.environment_vars.items():
                cmd.extend(['-e', f'{key}={value}'])
        
        # Mount source paths for backup operations
        if self.source_paths and self.command_type == CommandType.BACKUP:
            for source_path in self.source_paths:
                # Mount actual path as itself (no artificial /backup-source-{i} names)
                cmd.extend(['-v', f'{source_path}:{source_path}:ro'])
        
        # For restore operations, mount target directory
        if self.command_type == CommandType.RESTORE:
            target_path = self._extract_target_from_args()
            if target_path == '/' and hasattr(self, 'job_config') and self.job_config:
                # For restore-to-source, introspect snapshot to determine what paths to mount
                snapshot_id = self._extract_snapshot_id_from_args()
                if snapshot_id:
                    snapshot_paths = self._get_snapshot_root_paths(snapshot_id)
                    for path in snapshot_paths:
                        # Mount exactly what's in the snapshot - let natural failures occur
                        cmd.extend(['-v', f'{path}:{path}'])
            elif target_path:
                # For restore-to-highball, mount target directory
                cmd.extend(['-v', f'{target_path}:/restore-target'])
        
        # Use official restic container
        cmd.append('restic/restic:0.18.0')
        
        # Add restic repository
        cmd.extend(['-r', self.repository_url])
        
        # Add command type
        cmd.append(self.command_type.value)
        
        # Add command-specific arguments (adjust paths for container)
        if self.args:
            adjusted_args = self._adjust_args_for_container()
            cmd.extend(adjusted_args)
            
        # Add container source paths for backup operations
        if self.source_paths and self.command_type == CommandType.BACKUP:
            for source_path in self.source_paths:
                # Use actual source paths in backup command
                cmd.append(source_path)
        
        return cmd
    
    def _extract_target_from_args(self) -> str:
        """Extract target directory from restore arguments"""
        if not self.args:
            return ""
        
        try:
            target_idx = self.args.index('--target')
            if target_idx + 1 < len(self.args):
                return self.args[target_idx + 1]
        except ValueError:
            pass
        
        return ""
    
    def _extract_snapshot_id_from_args(self) -> str:
        """Extract snapshot ID from restore arguments"""
        if not self.args:
            return ""
        
        # First argument after 'restore' command is snapshot ID
        for arg in self.args:
            if arg not in ['--target', '--include', '--exclude', '--dry-run', '--json'] and not arg.startswith('-'):
                return arg
        
        return ""
    
    def _get_snapshot_root_paths(self, snapshot_id: str) -> List[str]:
        """Get root paths from snapshot by introspecting its contents"""
        if not snapshot_id or not hasattr(self, 'job_config') or not self.job_config:
            return []
        
        try:
            # Build restic command to list snapshot contents
            dest_config = self.job_config.get('dest_config', {})
            repo_url = self._build_repository_url(dest_config)
            env_vars = self._build_environment(dest_config)
            
            # Use BackupClient to execute restic ls command
            from services.backup_client import BackupClient
            
            if self.transport == TransportType.SSH:
                # Execute via SSH using container (restic not installed on remote host)
                hostname = self.ssh_config.get('hostname', '')
                username = self.ssh_config.get('username', '') 
                
                # Build container command for snapshot introspection
                runtime = self.job_config.get('container_runtime', 'docker')
                container_cmd = [runtime, 'run', '--rm', '--user', '$(id -u):$(id -g)']
                
                # Add environment variables
                for key, value in env_vars.items():
                    container_cmd.extend(['-e', f'{key}={value}'])
                
                # Use restic container for ls command
                container_cmd.extend(['restic/restic:0.18.0', '-r', repo_url, 'ls', snapshot_id])
                
                # Execute container command via SSH
                import shlex
                container_cmd_str = shlex.join(container_cmd)
                container_cmd_str = container_cmd_str.replace("'$(id -u):$(id -g)'", "$(id -u):$(id -g)")
                
                result = BackupClient.execute_via_ssh(hostname, username, container_cmd_str, {}, timeout=30)
            else:
                # Execute locally
                command = ['restic', '-r', repo_url, 'ls', snapshot_id]
                result = BackupClient.execute_locally(command, env_vars, timeout=30)
            
            if result.get('success'):
                # Parse output to extract root directory paths
                lines = result.get('stdout', '').strip().split('\n')
                root_paths = set()
                
                for line in lines:
                    line = line.strip()
                    if line and line.startswith('/'):
                        # Extract top-level directory (e.g., /home from /home/user/file.txt)
                        parts = line.split('/')
                        if len(parts) >= 2:
                            root_path = '/' + parts[1]  # e.g., /home, /backup-source-0
                            root_paths.add(root_path)
                
                return list(root_paths)
                
        except Exception as e:
            # If introspection fails, return empty list - restore will fail gracefully
            pass
            
        return []
    
    def _build_repository_url(self, dest_config: Dict) -> str:
        """Get Restic repository URL from destination config"""
        return dest_config.get('repo_uri', dest_config.get('dest_string', '/tmp/restic-repo'))
    
    def _build_environment(self, dest_config: Dict) -> Dict[str, str]:
        """Build environment variables for Restic execution"""
        env = {}
        if 'password' in dest_config:
            env['RESTIC_PASSWORD'] = dest_config['password']
        return env
    
    def _adjust_args_for_container(self) -> List[str]:
        """Adjust arguments for container execution (update paths)"""
        if not self.args:
            return []
        
        adjusted = []
        i = 0
        while i < len(self.args):
            arg = self.args[i]
            
            # Adjust target path for restore operations  
            if arg == '--target' and i + 1 < len(self.args):
                adjusted.append('--target')
                adjusted.append('/restore-target')
                i += 2
            # Keep include paths as-is (they reference backup content paths)
            elif arg == '--include' and i + 1 < len(self.args):
                adjusted.append('--include')
                adjusted.append(self.args[i + 1])
                i += 2
            else:
                adjusted.append(arg)
                i += 1
        
        return adjusted


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
        backup_args = self._build_backup_args(job_config)
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
            forget_args = self._build_retention_args(retention)
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
        restore_args = self._build_restore_args(restore_config_with_job)
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
    
    def _build_backup_args(self, job_config: Dict) -> List[str]:
        """Build arguments for backup command"""
        args = []
        
        # Add JSON output for parsing
        args.append('--json')
        
        # Add tags
        tags = job_config.get('tags', [])
        for tag in tags:
            args.extend(['--tag', tag])
        
        # Add exclude patterns
        excludes = job_config.get('exclude_patterns', [])
        for pattern in excludes:
            args.extend(['--exclude', pattern])
        
        # Add verbose output if requested
        if job_config.get('verbose', True):  # Default to verbose for better logging
            args.append('--verbose')
        
        return args
    
    def _build_retention_args(self, retention: Dict) -> List[str]:
        """Build arguments for retention policy"""
        args = ['--prune']  # Auto-prune when forgetting
        
        if 'keep_daily' in retention:
            args.extend(['--keep-daily', str(retention['keep_daily'])])
        if 'keep_weekly' in retention:
            args.extend(['--keep-weekly', str(retention['keep_weekly'])])
        if 'keep_monthly' in retention:
            args.extend(['--keep-monthly', str(retention['keep_monthly'])])
        if 'keep_yearly' in retention:
            args.extend(['--keep-yearly', str(retention['keep_yearly'])])
        
        return args
    
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
    
    def _build_restore_args(self, restore_config: Dict) -> List[str]:
        """Build arguments for restore command"""
        args = []
        
        # Add snapshot ID first (must come immediately after 'restore' command)
        snapshot_id = restore_config.get('snapshot_id', 'latest')
        if snapshot_id:
            args.append(snapshot_id)
        
        # Add target directory
        restore_target = restore_config.get('restore_target', 'highball')
        if restore_target == 'highball':
            args.extend(['--target', '/restore'])
        elif restore_target == 'source':
            # For restore-to-source, restore to root and let mount mapping handle the paths
            args.extend(['--target', '/'])
        
        # Add selected paths (for granular restore)
        if not restore_config.get('select_all', False):
            selected_paths = restore_config.get('selected_paths', [])
            for path in selected_paths:
                if path.strip():
                    args.extend(['--include', path])
        
        # Add dry run flag
        if restore_config.get('dry_run', False):
            args.append('--dry-run')
        
        # Add JSON output for progress tracking
        if not restore_config.get('dry_run', False):
            args.append('--json')
        
        return args
    
    def _estimate_restore_duration(self, restore_config: Dict) -> int:
        """Estimate restore duration in minutes"""
        # Simple heuristic - restores are typically faster than backups
        if restore_config.get('select_all', False):
            return 30  # Full restore
        else:
            path_count = len(restore_config.get('selected_paths', []))
            return max(5, min(60, path_count * 2))  # 2 minutes per selected path