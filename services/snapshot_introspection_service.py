"""
Snapshot introspection service for Restic repositories
Handles discovery of paths and metadata from backup snapshots
"""
from typing import Dict, List, Optional
from services.command_execution_service import CommandExecutionService


class SnapshotIntrospectionService:
    """Service for introspecting Restic snapshot contents and metadata"""
    
    def __init__(self):
        self.timeout = 30  # seconds for introspection commands
    
    def get_snapshot_source_paths(
        self,
        snapshot_id: str,
        repository_url: str,
        environment_vars: Dict[str, str],
        ssh_config: Optional[Dict[str, str]] = None,
        container_runtime: str = 'docker'
    ) -> List[str]:
        """
        Get the original source paths that were backed up in a snapshot
        
        Args:
            snapshot_id: The snapshot ID to introspect
            repository_url: Restic repository URL
            environment_vars: Environment variables (passwords, etc.)
            ssh_config: SSH configuration if remote execution needed
            container_runtime: Container runtime (docker/podman)
            
        Returns:
            List of original source paths from the snapshot
        """
        try:
            if ssh_config:
                # Execute via SSH using container (restic not installed on remote hosts)
                result = self._execute_via_ssh(
                    snapshot_id, repository_url, environment_vars,
                    ssh_config, container_runtime
                )
            else:
                # Execute locally
                result = self._execute_locally(
                    snapshot_id, repository_url, environment_vars
                )
            
            if result.get('success'):
                return self._parse_snapshot_paths(result.get('stdout', ''))
            
        except Exception:
            # If introspection fails, return empty list - operations will fail gracefully
            pass
            
        return []
    
    def _execute_via_ssh(
        self,
        snapshot_id: str,
        repository_url: str,
        environment_vars: Dict[str, str],
        ssh_config: Dict[str, str],
        container_runtime: str
    ) -> Dict:
        """Execute snapshot introspection via SSH using container"""
        hostname = ssh_config.get('hostname', '')
        username = ssh_config.get('username', '')
        
        # Build container command for snapshot introspection
        container_cmd = [container_runtime, 'run', '--rm', '--user', '$(id -u):$(id -g)']
        
        # Add environment variables
        for key, value in environment_vars.items():
            container_cmd.extend(['-e', f'{key}={value}'])
        
        # Use restic container for ls command
        container_cmd.extend(['restic/restic:0.18.0', '-r', repository_url, 'ls', snapshot_id])
        
        # Execute container command via SSH
        import shlex
        container_cmd_str = shlex.join(container_cmd)
        container_cmd_str = container_cmd_str.replace("'$(id -u):$(id -g)'", "$(id -u):$(id -g)")
        
        executor = CommandExecutionService()
        result = executor.execute_container_via_ssh(hostname, username, container_cmd)
        return {
            'success': result.success,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    
    def _execute_locally(
        self,
        snapshot_id: str,
        repository_url: str,
        environment_vars: Dict[str, str]
    ) -> Dict:
        """Execute snapshot introspection locally"""
        command = ['restic', '-r', repository_url, 'ls', snapshot_id]
        executor = CommandExecutionService()
        result = executor.execute_locally(command, environment_vars)
        return {
            'success': result.success,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    
    def _parse_snapshot_paths(self, output: str) -> List[str]:
        """
        Parse restic ls output to extract original backup source paths
        
        Looks for the snapshot info line format:
        "snapshot abc123 of [/path1,/path2] at timestamp"
        """
        lines = output.strip().split('\n')
        
        # Look for the snapshot info line that shows the original paths
        for line in lines:
            line = line.strip()
            if 'snapshot' in line and 'of [' in line and '] at' in line:
                # Extract paths from: "snapshot abc123 of [/path1,/path2] at timestamp"
                start = line.find('of [') + 4
                end = line.find('] at')
                if start > 3 and end > start:
                    paths_str = line[start:end]
                    # Split by comma and clean up paths
                    snapshot_paths = [p.strip() for p in paths_str.split(',')]
                    return [p for p in snapshot_paths if p]
        
        return []