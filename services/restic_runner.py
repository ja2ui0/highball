"""
Restic backup service
Handles Restic backup operations via SSH execution, similar to rsync pattern
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class TransportType(Enum):
    """Transport methods for Restic operations"""
    LOCAL = "local"
    SSH = "ssh"
    CONTAINER = "container"


class CommandType(Enum):
    """Types of Restic commands"""
    INIT = "init"
    BACKUP = "backup"
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
    
    def to_ssh_command(self) -> List[str]:
        """Convert to SSH command array for execution"""
        if self.transport != TransportType.SSH:
            return self.to_local_command()
        
        # Build environment variable exports
        env_exports = []
        if self.environment_vars:
            for key, value in self.environment_vars.items():
                env_exports.append(f"export {key}='{value}'")
        
        # Build restic command
        restic_cmd = ["restic", "-r", self.repository_url]
        if self.args:
            restic_cmd.extend(self.args)
        if self.source_paths and self.command_type == CommandType.BACKUP:
            restic_cmd.extend(self.source_paths)
        
        # Combine environment setup and restic command
        remote_command = "; ".join(env_exports + [" ".join(restic_cmd)])
        
        # Build SSH command
        ssh_cmd = [
            'ssh', '-o', 'ConnectTimeout=30', '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null',
            f"{self.ssh_config['username']}@{self.ssh_config['hostname']}",
            remote_command
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
                args=[]
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
            timeout_seconds=job_config.get('timeout', self.default_timeout)
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
                environment_vars=environment_vars
            )
            commands.append(forget_cmd)
            
            # Prune after forget
            prune_cmd = ResticCommand(
                command_type=CommandType.PRUNE,
                transport=transport,
                ssh_config=ssh_config,
                repository_url=repository_url,
                args=[],
                environment_vars=environment_vars
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
        """Build Restic repository URL from destination config"""
        repo_type = dest_config.get('repo_type', 'local')
        location = dest_config.get('repo_location', '/tmp/restic-repo')
        
        if repo_type == 'local':
            return location
        elif repo_type == 'sftp':
            hostname = dest_config.get('repo_hostname', 'localhost')
            path = dest_config.get('repo_path', '/backup')
            user = dest_config.get('repo_username', 'backup')
            return f"sftp:{user}@{hostname}:{path}"
        elif repo_type == 's3':
            bucket = dest_config.get('s3_bucket', 'my-backup-bucket')
            prefix = dest_config.get('s3_prefix', '')
            if prefix:
                return f"s3:{bucket}/{prefix}"
            return f"s3:{bucket}"
        else:
            return location
    
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
        """Parse source paths from source configuration"""
        if 'paths' in source_config:
            return source_config['paths']
        elif 'path' in source_config:
            return [source_config['path']]
        else:
            return ['/home']  # Default backup path for SSH sources
    
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